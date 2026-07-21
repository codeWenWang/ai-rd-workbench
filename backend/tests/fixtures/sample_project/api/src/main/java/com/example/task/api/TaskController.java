package com.example.task.api;

import com.example.task.domain.CreateTaskRequest;
import com.example.task.domain.TaskResponse;
import com.example.task.domain.UpdateTaskRequest;
import com.example.task.service.TaskService;
import java.util.List;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/tasks")
public class TaskController {
    private final TaskService taskService;

    public TaskController(TaskService taskService) {
        this.taskService = taskService;
    }

    /** 查询研发任务列表 */
    @GetMapping
    public ApiResponse<List<TaskResponse>> listTasks() {
        return ApiResponse.success(taskService.listTasks());
    }

    /** 创建研发任务 */
    @PostMapping
    public ApiResponse<TaskResponse> createTask(@RequestBody CreateTaskRequest request) {
        return ApiResponse.success(taskService.createTask(request));
    }

    /** 根据 ID 查询研发任务 */
    @GetMapping("/{id}")
    public ApiResponse<TaskResponse> getTask(@PathVariable Long id) {
        return ApiResponse.success(taskService.getTask(id));
    }

    /** 更新研发任务 */
    @PutMapping("/{id}")
    public ApiResponse<TaskResponse> updateTask(
        @PathVariable Long id,
        @RequestBody UpdateTaskRequest request
    ) {
        return ApiResponse.success(taskService.updateTask(id, request));
    }

    /** 删除研发任务 */
    @DeleteMapping("/{id}")
    public ApiResponse<Void> deleteTask(@PathVariable Long id) {
        taskService.deleteTask(id);
        return ApiResponse.success(null);
    }

    /** 完成研发任务 */
    @PutMapping("/{id}/complete")
    public ApiResponse<TaskResponse> completeTask(@PathVariable Long id) {
        return ApiResponse.success(taskService.completeTask(id));
    }
}
