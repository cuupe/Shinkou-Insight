package com.cuupe.backend.modules.notification.service;

import com.cuupe.backend.modules.notification.mapper.NotificationMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class NotificationService {
    private final NotificationMapper mapper;

    public void create(
            Long workspaceId,
            Long recipientUserId,
            Long projectId,
            String kind,
            String title,
            String body,
            String routeName
    ) {
        mapper.insert(workspaceId, recipientUserId, projectId, kind, title, body, routeName);
    }
}
