package com.example.task.api;

import com.example.task.repository.InMemoryTaskRepository;
import com.example.task.repository.TaskRepository;
import com.example.task.service.DefaultTaskService;
import com.example.task.service.TaskService;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

@SpringBootApplication
public class TaskApplication {
    public static void main(String[] args) {
        SpringApplication.run(TaskApplication.class, args);
    }

    @Bean
    public TaskRepository taskRepository() {
        return new InMemoryTaskRepository();
    }

    @Bean
    public TaskService taskService(TaskRepository repository) {
        return new DefaultTaskService(repository);
    }
}
