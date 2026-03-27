import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_client.dart';
import 'api_exception.dart';
import 'endpoints.dart';

enum HealthStatus { ok, degraded }

final healthServiceProvider = Provider<HealthService>((ref) {
  final client = ref.read(apiClientProvider);
  return HealthService(client);
});

class HealthService {
  final ApiClient _client;

  HealthService(this._client);

  Future<HealthStatus> checkHealth() async {
    try {
      final resp = await _client.get<Map<String, dynamic>>(Endpoints.health);
      final status = resp['status'] as String? ?? 'degraded';
      return status == 'ok' ? HealthStatus.ok : HealthStatus.degraded;
    } on ApiException catch (_) {
      return HealthStatus.degraded;
    }
  }
}
