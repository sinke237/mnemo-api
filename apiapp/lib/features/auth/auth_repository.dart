import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import '../../core/api/endpoints.dart';

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  final client = ref.read(apiClientProvider);
  final storage = const FlutterSecureStorage();
  final repo = AuthRepository(client, storage);
  // Ensure ApiClient notifies repository on 401
  client.setOnUnauthorized(() async {
    await repo._handleUnauthorized();
  });
  return repo;
});

class AuthRepository {
  static const _kApiKey = 'mnemo_api_key';
  static const _kUserId = 'mnemo_user_id';

  final ApiClient _client;
  final FlutterSecureStorage _storage;

  String? _accessToken;

  AuthRepository(this._client, this._storage);

  /// Register a new user. Note: server requires admin scope for POST /v1/users.
  /// The API source requires admin scope; callers should handle 403 accordingly.
  Future<Map<String, dynamic>> register({
    String? displayName,
    required String country,
    String? timezone,
    String? educationLevel,
    int? dailyGoal,
  }) async {
    final body = <String, dynamic>{
      'display_name': displayName,
      'country': country,
      'timezone': timezone,
      'education_level': educationLevel,
      'daily_goal_cards': dailyGoal,
    }..removeWhere((k, v) => v == null);

    final resp = await _client.post<Map<String, dynamic>>(Endpoints.users, data: body);
    return resp;
  }

  /// Exchange apiKey+userId for JWT and store credentials securely.
  Future<void> login({required String apiKey, required String userId}) async {
    try {
      final resp = await _client.post<Map<String, dynamic>>(Endpoints.authToken, data: {
        'user_id': userId,
        'api_key': apiKey,
      });

      final accessToken = resp['access_token'] as String?;
      if (accessToken == null) {
        throw ApiException(500, 'Missing access token in response');
      }

      _accessToken = accessToken;
      _client.setToken(_accessToken);

      // persist api_key and user_id only (JWT is in-memory per spec)
      await _storage.write(key: _kApiKey, value: apiKey);
      await _storage.write(key: _kUserId, value: userId);
    } on ApiException {
      rethrow;
    }
  }

  /// Re-exchange stored api_key+user_id for a fresh JWT. Returns true when refreshed.
  Future<bool> refreshToken() async {
    final apiKey = await _storage.read(key: _kApiKey);
    final userId = await _storage.read(key: _kUserId);
    if (apiKey == null || userId == null) return false;

    try {
      final resp = await _client.post<Map<String, dynamic>>(Endpoints.authToken, data: {
        'user_id': userId,
        'api_key': apiKey,
      });
      final accessToken = resp['access_token'] as String?;
      if (accessToken == null) return false;
      _accessToken = accessToken;
      _client.setToken(_accessToken);
      return true;
    } on ApiException {
      // If the exchange fails (401), clear stored credentials
      await _clearStoredCredentials();
      rethrow;
    }
  }

  Future<void> logout() async {
    _accessToken = null;
    _client.setToken(null);
    await _clearStoredCredentials();
  }

  Future<void> _clearStoredCredentials() async {
    await _storage.delete(key: _kApiKey);
    await _storage.delete(key: _kUserId);
  }

  /// Called by ApiClient when a 401 is detected
  Future<void> _handleUnauthorized() async {
    // Clear in-memory token and persistent credentials; callers should navigate to onboarding
    _accessToken = null;
    _client.setToken(null);
    await _clearStoredCredentials();
  }

  /// True if an API key + user id are stored locally (i.e., device has onboarding completed)
  Future<bool> isAuthenticated() async {
    final apiKey = await _storage.read(key: _kApiKey);
    final userId = await _storage.read(key: _kUserId);
    return apiKey != null && userId != null;
  }

  Future<String?> getCurrentUserId() async {
    return await _storage.read(key: _kUserId);
  }
}
