import 'dart:async';

import 'package:dio/dio.dart';

import 'api_exception.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Riverpod provider for ApiClient. Base URL can be overridden with
/// `--dart-define=MNEMO_API_BASE_URL=https://...` at build/run time.
final apiClientProvider = Provider<ApiClient>((ref) {
  const defaultBase = String.fromEnvironment('MNEMO_API_BASE_URL',
      defaultValue: 'https://api.mnemo.app');
  return ApiClient(baseUrl: defaultBase);
});

/// API client wrapper around Dio used by repositories/services.
class ApiClient {
  final Dio _dio;
  String? _accessToken;
  void Function()? _onUnauthorized;

  ApiClient({required String baseUrl}) : _dio = Dio(BaseOptions(
    baseUrl: baseUrl,
    connectTimeout: const Duration(seconds: 15),
    receiveTimeout: const Duration(seconds: 30),
    sendTimeout: const Duration(seconds: 30),
    responseType: ResponseType.json,
  )) {
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        if (_accessToken != null && _accessToken!.isNotEmpty) {
          options.headers['Authorization'] = 'Bearer $_accessToken';
        }
        return handler.next(options);
      },
      onError: (err, handler) {
        // Network-level errors
        if (err.type == DioExceptionType.connectionTimeout ||
            err.type == DioExceptionType.receiveTimeout ||
            err.type == DioExceptionType.sendTimeout ||
            err.type == DioExceptionType.connectionError) {
          handler.reject(err);
          return;
        }

        final response = err.response;

        if (response != null) {
          if (response.statusCode == 401) {
            // Notify consumer so it can clear credentials and redirect
            _onUnauthorized?.call();
          }

          // Try to parse standardized API error body {"error": {...}}
          try {
            final data = response.data;
            if (data is Map && data['error'] is Map) {
              final apiErr = ApiError.fromMap(Map<String, dynamic>.from(data['error']));
              handler.reject(DioException(
                requestOptions: err.requestOptions,
                response: response,
                error: ApiException(response.statusCode ?? 0, apiErr.message, apiError: apiErr),
                type: err.type,
              ));
              return;
            }
          } catch (_) {
            // fall through to default
          }
        }

        handler.next(err);
      },
    ));
  }

  void setToken(String? token) {
    _accessToken = token;
  }

  void setOnUnauthorized(void Function()? callback) {
    _onUnauthorized = callback;
  }

  Future<Response<T>> _perform<T>(Future<Response<T>> future) async {
    try {
      final resp = await future;
      return resp;
    } on DioException catch (e) {
      // If the DioException carries our ApiException inside error
      if (e.error is ApiException) {
        throw e.error as ApiException;
      }

      final isNetwork = e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout ||
          e.type == DioExceptionType.sendTimeout ||
          e.type == DioExceptionType.connectionError ||
          e.type == DioExceptionType.badCertificate;

      // Prefer message if available; fall back to error's toString
      final message = (e.message != null && e.message!.isNotEmpty)
          ? e.message!
          : (e.error?.toString() ?? 'Network error');

      throw ApiException(
        e.response?.statusCode ?? 0,
        message,
        networkError: isNetwork,
      );
    }
  }

  Future<T> get<T>(String path, {Map<String, dynamic>? queryParameters}) async {
    final resp = await _perform(_dio.get<T>(path, queryParameters: queryParameters));
    return resp.data as T;
  }

  Future<T> post<T>(String path, {dynamic data, Map<String, dynamic>? queryParameters}) async {
    final resp = await _perform(_dio.post<T>(path, data: data, queryParameters: queryParameters));
    return resp.data as T;
  }

  Future<T> put<T>(String path, {dynamic data}) async {
    final resp = await _perform(_dio.put<T>(path, data: data));
    return resp.data as T;
  }

  Future<T> patch<T>(String path, {dynamic data}) async {
    final resp = await _perform(_dio.patch<T>(path, data: data));
    return resp.data as T;
  }

  Future<T> delete<T>(String path, {dynamic data}) async {
    final resp = await _perform(_dio.delete<T>(path, data: data));
    return resp.data as T;
  }
}
