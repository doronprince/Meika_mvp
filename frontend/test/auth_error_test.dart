// What the sign-in and sign-up screens tell you when a request fails. A
// rejected email used to read "could not reach the server", which sends
// people to check their connection over a typo.

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:meika/data/repositories/auth_repository.dart';

DioException _withResponse(int statusCode, dynamic body) {
  final options = RequestOptions(path: '/auth/register');
  return DioException(
    requestOptions: options,
    response: Response(requestOptions: options, statusCode: statusCode, data: body),
    type: DioExceptionType.badResponse,
  );
}

void main() {
  test('an invalid email explains the address, not the network', () {
    // FastAPI sends validation errors as a list, which is why the old
    // string-only check missed them.
    final error = _withResponse(422, {
      'detail': [
        {
          'type': 'value_error',
          'loc': ['body', 'email'],
          'msg': 'value is not a valid email address: The part after the @-sign is not valid. It should have a period.',
        }
      ]
    });

    final message = authErrorMessage(error);
    expect(message, contains('email address'));
    expect(message, contains('name@example.com'));
    expect(message.toLowerCase(), isNot(contains('connection')));
  });

  test('the server’s own message is passed through', () {
    expect(
      authErrorMessage(_withResponse(401, {'detail': 'Incorrect email or password'})),
      'Incorrect email or password',
    );
  });

  test('rate limiting says to wait', () {
    expect(authErrorMessage(_withResponse(429, {'detail': 'Too many requests'})), contains('wait a moment'));
  });

  test('a timeout mentions the server waking, not the connection', () {
    final error = DioException(
      requestOptions: RequestOptions(path: '/auth/login'),
      type: DioExceptionType.connectionTimeout,
    );
    expect(authErrorMessage(error), contains('wake'));
  });

  test('a genuine connection failure still says so', () {
    final error = DioException(
      requestOptions: RequestOptions(path: '/auth/login'),
      type: DioExceptionType.connectionError,
    );
    expect(authErrorMessage(error), contains('Could not reach the server'));
  });
}
