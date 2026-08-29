package com.cuupe.backend.modules.notification.mapper;

import com.cuupe.backend.modules.notification.entity.Notification;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface NotificationMapper {
    List<Notification> findByWorkspaceAndUser(
            @Param("workspaceId") Long workspaceId,
            @Param("userId") Long userId
    );

    int insert(
            @Param("workspaceId") Long workspaceId,
            @Param("recipientUserId") Long recipientUserId,
            @Param("projectId") Long projectId,
            @Param("kind") String kind,
            @Param("title") String title,
            @Param("body") String body,
            @Param("routeName") String routeName
    );

    int markRead(
            @Param("id") Long id,
            @Param("workspaceId") Long workspaceId,
            @Param("userId") Long userId
    );

    int markAllRead(
            @Param("workspaceId") Long workspaceId,
            @Param("userId") Long userId
    );
}
