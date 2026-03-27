class ApiError {
  final String code;
  final String message;
  final int status;
  final String? requestId;
  final Map<String, dynamic>? details;
  final Map<String, String>? resource;

  ApiError({
    required this.code,
    required this.message,
    required this.status,
    this.requestId,
    this.details,
    this.resource,
  });

  factory ApiError.fromMap(Map<String, dynamic> map) {
    return ApiError(
      code: map['code']?.toString() ?? 'UNKNOWN',
      message: map['message']?.toString() ?? '',
      status: (map['status'] is int) ? map['status'] as int : int.tryParse('${map['status']}') ?? 0,
      requestId: map['request_id'] as String?,
      details: (map['details'] is Map) ? Map<String, dynamic>.from(map['details']) : null,
      resource: (map['resource'] is Map) ? Map<String, String>.from(map['resource']) : null,
    );
  }
}

/// Exception thrown for API errors
class ApiException implements Exception {
  final int statusCode;
  final String message;
  final ApiError? apiError;
  final bool networkError;

  ApiException(
    this.statusCode,
    this.message, {
    this.apiError,
    this.networkError = false,
  });

  bool get isNetworkError => networkError;

  @override
  String toString() => 'ApiException($statusCode): $message';
}
