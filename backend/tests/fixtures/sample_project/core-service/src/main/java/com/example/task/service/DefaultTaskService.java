package com.example.task.service;

import com.example.task.domain.CreateTaskRequest;
import com.example.task.domain.Task;
import com.example.task.domain.TaskResponse;
import com.example.task.domain.TaskStatus;
import com.example.task.domain.UpdateTaskRequest;
import com.example.task.repository.TaskRepository;
import java.time.LocalDateTime;
import java.util.List;

public class DefaultTaskService implements TaskService {
    private final TaskRepository repository;

    public DefaultTaskService(TaskRepository repository) {
        this.repository = repository;
    }

    @Override
    public List<TaskResponse> listTasks() {
        return repository.findAll().stream().map(this::toResponse).toList();
    }

    @Override
    public TaskResponse getTask(Long id) {
        return toResponse(requireTask(id));
    }

    @Override
    public TaskResponse createTask(CreateTaskRequest request) {
        LocalDateTime now = LocalDateTime.now();
        Task task = new Task(now.hashCode() & 0xffffL, request.title(), request.owner(),
            TaskStatus.TODO, now, now);
        return toResponse(repository.save(task));
    }

    @Override
    public TaskResponse updateTask(Long id, UpdateTaskRequest request) {
        Task current = requireTask(id);
        Task updated = new Task(id, request.title(), request.owner(), request.status(),
            current.createdAt(), LocalDateTime.now());
        return toResponse(repository.save(updated));
    }

    @Override
    public TaskResponse completeTask(Long id) {
        Task current = requireTask(id);
        Task completed = new Task(id, current.title(), current.owner(), TaskStatus.DONE,
            current.createdAt(), LocalDateTime.now());
        return toResponse(repository.save(completed));
    }

    @Override
    public void deleteTask(Long id) {
        requireTask(id);
        repository.deleteById(id);
    }

    private Task requireTask(Long id) {
        return repository.findById(id)
            .orElseThrow(() -> new TaskNotFoundException(id));
    }

    private TaskResponse toResponse(Task task) {
        return new TaskResponse(task.id(), task.title(), task.owner(), task.status(),
            task.createdAt(), task.updatedAt());
    }
}
