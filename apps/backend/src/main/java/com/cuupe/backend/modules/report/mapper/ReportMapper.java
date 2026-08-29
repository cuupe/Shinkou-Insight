package com.cuupe.backend.modules.report.mapper;
import com.cuupe.backend.modules.report.entity.Report; import org.apache.ibatis.annotations.*; import java.util.List;
@Mapper public interface ReportMapper { List<Report> findByProject(@Param("projectId") Long projectId,@Param("userId") Long userId); Report findById(@Param("id") Long id,@Param("projectId") Long projectId,@Param("userId") Long userId); int update(Report report); }
