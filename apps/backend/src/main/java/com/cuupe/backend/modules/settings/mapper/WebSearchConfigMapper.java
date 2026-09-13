package com.cuupe.backend.modules.settings.mapper;

import com.cuupe.backend.modules.settings.entity.WebSearchConfig;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface WebSearchConfigMapper {
    WebSearchConfig findByProject(@Param("projectId") Long projectId, @Param("userId") Long userId);

    WebSearchConfig findForRuntime(@Param("projectId") Long projectId, @Param("userId") Long userId);

    int insert(WebSearchConfig config);

    int update(WebSearchConfig config);
}
