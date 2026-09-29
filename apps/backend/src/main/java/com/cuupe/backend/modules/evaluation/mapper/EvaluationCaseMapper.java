package com.cuupe.backend.modules.evaluation.mapper;

import com.cuupe.backend.modules.evaluation.entity.EvaluationCase;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface EvaluationCaseMapper {
    List<EvaluationCase> findByWorkspace(
            @Param("workspaceId") Long workspaceId,
            @Param("userId") Long userId
    );

    EvaluationCase findById(
            @Param("workspaceId") Long workspaceId,
            @Param("id") Long id,
            @Param("userId") Long userId
    );

    int updateStatus(
            @Param("workspaceId") Long workspaceId,
            @Param("id") Long id,
            @Param("userId") Long userId,
            @Param("status") String status
    );

    int insert(EvaluationCase item);
}
