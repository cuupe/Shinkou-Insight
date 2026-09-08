package com.cuupe.backend.modules.auth.service;

import com.cuupe.backend.config.security.AuthSecurityProperties;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.session.SessionInformation;
import org.springframework.security.core.session.SessionRegistry;
import org.springframework.stereotype.Service;

import java.util.Arrays;
import java.util.Comparator;

/** Keeps manually-created session authentications subject to a bounded limit. */
@Service
@RequiredArgsConstructor
public class SessionSecurityService {
    private final SessionRegistry sessionRegistry;
    private final AuthSecurityProperties properties;

    public void register(String sessionId, String principal) {
        if (sessionId == null || principal == null) return;
        SessionInformation[] active = activeSessions(principal);
        int allowedExisting = Math.max(0, properties.getMaxActiveSessionsPerUser() - 1);
        Arrays.stream(active)
                .sorted(Comparator.comparing(SessionInformation::getLastRequest))
                .limit(Math.max(0, active.length - allowedExisting))
                .forEach(SessionInformation::expireNow);
        sessionRegistry.registerNewSession(sessionId, principal);
    }

    public void expireOtherSessions(String principal, String currentSessionId) {
        for (SessionInformation session : activeSessions(principal)) {
            if (!session.getSessionId().equals(currentSessionId)) session.expireNow();
        }
    }

    public void expireAllSessions(String principal) {
        for (SessionInformation session : activeSessions(principal)) session.expireNow();
    }

    public void remove(String sessionId) {
        if (sessionId != null) sessionRegistry.removeSessionInformation(sessionId);
    }

    private SessionInformation[] activeSessions(String principal) {
        return sessionRegistry.getAllSessions(principal, false).toArray(SessionInformation[]::new);
    }
}
