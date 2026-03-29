import importlib.resources as resources


async def test_request_password_reset_renders_template_and_fragment(db, client, monkeypatch):
    """Integration test that mocks the email sender to verify the reset URL
    uses a fragment-style token and that the email template is rendered.
    """
    # Create a user via the service helper so the request handler can find it
    from mnemo.schemas.user import UserProvisionRequest
    from mnemo.services import user as user_service

    user_data = UserProvisionRequest(
        email="alice@example.com",
        password="TestPass123",
        country="US",
        timezone="America/New_York",
    )

    user = await user_service.create_user(db, user_data)
    # Commit so the request-scoped session used by the test client can see the user
    await db.commit()

    # Capture calls to the email sender. We replace the sender with a
    # synchronous fake that renders the template locally and asserts it
    # contains the reset link.
    captured = []

    def fake_send_password_reset_email(email, reset_url, *, user_id=None):
        # Verify fragment-style token and frontend domain presence
        from mnemo.core.config import get_settings

        settings = get_settings()
        assert reset_url.startswith(f"{settings.frontend_base_url}/reset-password#token=")

        # Render the template that the real sender would use and ensure the
        # reset link appears in the rendered body (sanity check).
        tpl = resources.files("mnemo").joinpath("templates", "password_reset.txt").read_text()
        body = tpl.format(reset_link=reset_url)
        assert reset_url in body

        captured.append((email, reset_url, user_id))

    monkeypatch.setattr(
        "mnemo.services.email.send_password_reset_email", fake_send_password_reset_email
    )

    # Trigger the public endpoint that enqueues the background email task
    # Note: v1 router mounts user routes under /v1
    resp = await client.post("/v1/user/request-password-reset", json={"email": user.email})

    assert resp.status_code == 200
    # BackgroundTasks should have invoked our fake sender; ensure it was called
    assert captured, "Expected send_password_reset_email to be called"
    assert captured[0][0] == user.email
    assert captured[0][2] == user.id
