package com.cuupe.backend.common.exception;

import com.cuupe.backend.common.Result;
import jakarta.validation.ConstraintViolationException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.AuthenticationException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

import java.util.Objects;
import java.util.stream.Collectors;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(ApiException.class)
    public ResponseEntity<Result<Void>> handleApiException(ApiException exception) {
        return response(
                exception.getStatus(),
                exception.getCode(),
                exception.getMessage()
        );
    }

    @ExceptionHandler(AuthenticationException.class)
    public ResponseEntity<Result<Void>> handleAuthenticationException(
            AuthenticationException exception
    ) {
        log.warn("Authentication failed: {}", exception.getMessage());
        return response(
                HttpStatus.UNAUTHORIZED,
                "AUTH_LOGIN_FAILED",
                "手机号或密码错误"
        );
    }

    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<Result<Void>> handleAccessDeniedException(
            AccessDeniedException exception
    ) {
        return response(
                HttpStatus.FORBIDDEN,
                "ACCESS_DENIED",
                "当前账号没有执行此操作的权限"
        );
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Result<Void>> handleMethodArgumentNotValid(
            MethodArgumentNotValidException exception
    ) {
        String message = exception.getBindingResult()
                .getFieldErrors()
                .stream()
                .map(error -> error.getDefaultMessage())
                .filter(Objects::nonNull)
                .distinct()
                .collect(Collectors.joining("；"));

        return response(
                HttpStatus.BAD_REQUEST,
                "VALIDATION_ERROR",
                message.isBlank() ? "请求参数不正确" : message
        );
    }

    @ExceptionHandler(ConstraintViolationException.class)
    public ResponseEntity<Result<Void>> handleConstraintViolation(
            ConstraintViolationException exception
    ) {
        String message = exception.getConstraintViolations()
                .stream()
                .map(violation -> violation.getMessage())
                .filter(Objects::nonNull)
                .distinct()
                .collect(Collectors.joining("；"));

        return response(
                HttpStatus.BAD_REQUEST,
                "VALIDATION_ERROR",
                message.isBlank() ? "请求参数不正确" : message
        );
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<Result<Void>> handleUnreadableMessage() {
        return response(
                HttpStatus.BAD_REQUEST,
                "MALFORMED_REQUEST",
                "请求数据格式不正确"
        );
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<Result<Void>> handleTypeMismatch() {
        return response(
                HttpStatus.BAD_REQUEST,
                "INVALID_PARAMETER",
                "请求参数类型不正确"
        );
    }

    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    public ResponseEntity<Result<Void>> handleMethodNotSupported() {
        return response(
                HttpStatus.METHOD_NOT_ALLOWED,
                "METHOD_NOT_ALLOWED",
                "请求方式不支持"
        );
    }

    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public ResponseEntity<Result<Void>> handleMaxUploadSizeExceeded() {
        return response(
                HttpStatus.BAD_REQUEST,
                "FILE_TOO_LARGE",
                "单个文件必须小于 256 MB"
        );
    }

    @ExceptionHandler(DataIntegrityViolationException.class)
    public ResponseEntity<Result<Void>> handleDataIntegrityViolation(
            DataIntegrityViolationException exception
    ) {
        log.warn("Data integrity violation", exception);
        return response(
                HttpStatus.CONFLICT,
                "RESOURCE_CONFLICT",
                "提交的数据与现有记录冲突"
        );
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Result<Void>> handleUnexpectedException(Exception exception) {
        log.error("Unhandled request exception", exception);
        return response(
                HttpStatus.INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "服务器内部错误，请稍后重试"
        );
    }

    private ResponseEntity<Result<Void>> response(
            HttpStatus status,
            String code,
            String message
    ) {
        return ResponseEntity
                .status(status)
                .body(Result.fail(code, message));
    }
}
