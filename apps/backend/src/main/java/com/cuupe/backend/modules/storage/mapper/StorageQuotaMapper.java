package com.cuupe.backend.modules.storage.mapper;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface StorageQuotaMapper {
    @Insert("INSERT INTO user_storage_usage(user_id, used_bytes) VALUES(#{userId}, 0) ON CONFLICT (user_id) DO NOTHING")
    int ensureUser(@Param("userId") Long userId);

    @Select("SELECT used_bytes FROM user_storage_usage WHERE user_id = #{userId} FOR UPDATE")
    Long lockUsedBytes(@Param("userId") Long userId);

    @Select("SELECT used_bytes FROM user_storage_usage WHERE user_id = #{userId}")
    Long findUsedBytes(@Param("userId") Long userId);

    @Update("UPDATE user_storage_usage SET used_bytes = #{usedBytes}, updated_at = CURRENT_TIMESTAMP WHERE user_id = #{userId}")
    int updateUsedBytes(@Param("userId") Long userId, @Param("usedBytes") long usedBytes);

    @Select("SELECT COALESCE(SUM(file_size), 0)::BIGINT FROM agent_attachments WHERE uploaded_by = #{userId}")
    Long findFileBytes(@Param("userId") Long userId);

    @Select("SELECT COALESCE(SUM(file_size), 0)::BIGINT FROM knowledge_assets WHERE created_by = #{userId}")
    Long findKnowledgeBytes(@Param("userId") Long userId);
}
