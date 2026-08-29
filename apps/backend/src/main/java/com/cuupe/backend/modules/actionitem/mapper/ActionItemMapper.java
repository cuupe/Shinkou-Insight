package com.cuupe.backend.modules.actionitem.mapper;

import com.cuupe.backend.modules.actionitem.entity.ActionItem;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import java.util.List;

@Mapper
public interface ActionItemMapper {
    List<ActionItem> findByProject(@Param("projectId") Long projectId, @Param("userId") Long userId);
    ActionItem findById(@Param("id") Long id, @Param("projectId") Long projectId, @Param("userId") Long userId);
    int update(ActionItem item);
    int insert(ActionItem item);
}