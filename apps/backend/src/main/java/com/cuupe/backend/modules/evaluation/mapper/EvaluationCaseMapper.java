package com.cuupe.backend.modules.evaluation.mapper;
import com.cuupe.backend.modules.evaluation.entity.EvaluationCase; import org.apache.ibatis.annotations.*; import java.util.List;
@Mapper public interface EvaluationCaseMapper { List<EvaluationCase> findByWorkspace(@Param("workspaceId") Long workspaceId,@Param("userId") Long userId); int insert(EvaluationCase item); }