package com.cuupe.backend.modules.settings.mapper;
import com.cuupe.backend.modules.settings.entity.PromptVersion; import org.apache.ibatis.annotations.*; import java.util.List;
@Mapper public interface PromptVersionMapper { List<PromptVersion> findByWorkspace(@Param("workspaceId") Long workspaceId,@Param("userId") Long userId); int insert(PromptVersion prompt); int update(PromptVersion prompt); }