package com.cuupe.backend.modules.workspace.entity;
import tools.jackson.databind.annotation.JsonSerialize; import tools.jackson.databind.ser.std.ToStringSerializer; import lombok.Data; import java.time.LocalDateTime;
@Data public class Workspace {
    // 工作区主键使用雪花算法生成，超出 JS 安全整数范围，统一序列化为字符串
    @JsonSerialize(using = ToStringSerializer.class)
    private Long id;
    private String name;
    private String code;
    private String currentRole;
    private String description;
    private String status;
    private String preferences;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
