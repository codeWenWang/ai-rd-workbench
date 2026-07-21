package com.example.task.api;

import com.example.task.service.TaskNotFoundException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {
    @ExceptionHandler(TaskNotFoundException.class)
    public ApiResponse<Void> handleNotFound(TaskNotFoundException exception) {
        return new ApiResponse<>(0, exception.getMessage(), null);
    }
}
