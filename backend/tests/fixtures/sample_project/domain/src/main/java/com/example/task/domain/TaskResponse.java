package com.example.task.domain;

import java.time.LocalDateTime;

public record TaskResponse(
    Long id,
    String title,
    String owner,
    TaskStatus status,
    LocalDateTime createdAt,
    LocalDateTime updatedAt
) {}
