package com.example.task.domain;

public record UpdateTaskRequest(
    String title,
    String owner,
    TaskStatus status
) {}
