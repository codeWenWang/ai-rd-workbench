package com.example.task.service;

import com.example.task.domain.CreateTaskRequest;
import com.example.task.domain.TaskResponse;
import com.example.task.domain.UpdateTaskRequest;
import java.util.List;

public interface TaskService {
    List<TaskResponse> listTasks();
    TaskResponse getTask(Long id);
    TaskResponse createTask(CreateTaskRequest request);
    TaskResponse updateTask(Long id, UpdateTaskRequest request);
    TaskResponse completeTask(Long id);
    void deleteTask(Long id);
}
