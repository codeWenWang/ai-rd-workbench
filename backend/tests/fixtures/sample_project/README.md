# 研发任务管理演示项目

这是用于 AI 研发赋能平台课堂展示的最小多模块 Spring Boot 项目。

模块职责：

- `api`：REST 接口、统一响应和异常处理。
- `core-service`：研发任务业务规则。
- `data-repository`：任务持久化接口和内存实现。
- `domain`：任务领域模型和请求响应对象。

核心链路：客户端 -> TaskController -> TaskService -> TaskRepository -> Task。

运行方式（需要 JDK 17+ 和 Maven）：

```powershell
mvn -pl api -am spring-boot:run
```

启动后访问 `http://127.0.0.1:8080/api/tasks`。
