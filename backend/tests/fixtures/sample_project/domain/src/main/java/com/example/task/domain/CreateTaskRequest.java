package com.example.task.domain;

public record CreateTaskRequest(
    String title,
    String owner
) {}
