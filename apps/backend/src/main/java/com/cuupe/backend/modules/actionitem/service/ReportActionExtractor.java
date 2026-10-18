package com.cuupe.backend.modules.actionitem.service;

import com.cuupe.backend.modules.report.entity.Report;
import com.cuupe.backend.modules.project.service.ProjectReviewService;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDate;
import java.util.*;
import java.util.regex.Pattern;

/** Extracts explicit Markdown action sections for human confirmation, never task completion. */
public final class ReportActionExtractor {
    private ReportActionExtractor() {}
    public record Draft(String sourceKey,String title,String description,String acceptanceCriteria,
                        String ownerLabel,LocalDate dueAt,String priority,String sourceExcerpt) {}
    private static final Pattern HEADING=Pattern.compile("^(#{1,6})\\s+(.+)$");
    private static final Pattern SECTION=Pattern.compile("行动项|后续行动|行动计划|后续工作|后续计划|action items|next steps",Pattern.CASE_INSENSITIVE);
    private static final Pattern BULLET=Pattern.compile("^\\s*(?:[-*+] |\\d+[.、]\\s*)(?:\\[[ xX]\\]\\s*)?(.+)$");
    public static String hash(Report report) { return hash(ProjectReviewService.reportFields(report).toString()); }
    private static String hash(String value) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8))); }
        catch(Exception e) { throw new IllegalStateException(e); }
    }
    public static List<Draft> extract(Report report) {
        Map<String,Draft> result=new LinkedHashMap<>(); int level=0; List<String> header=null; String fence=null;
        for(String raw:Objects.toString(report.getContent(),"").split("\\R")) {
            String line=raw.trim();
            if(line.startsWith("```")||line.startsWith("~~~")) {
                String marker=line.substring(0,3);
                if(fence==null) fence=marker; else if(fence.equals(marker)) fence=null;
                continue;
            }
            if(fence!=null) continue;
            var heading=HEADING.matcher(line);
            if(heading.matches()) {
                int current=heading.group(1).length();
                if(SECTION.matcher(heading.group(2)).find()) { level=current;header=null; }
                else if(level>0&&current<=level) { level=0;header=null; }
                continue;
            }
            if(level==0||line.isBlank()||line.startsWith(">")) continue;
            if(line.startsWith("|")&&line.endsWith("|")) {
                List<String> cells=cells(line);
                if(cells.stream().allMatch(cell->cell.matches("[:\\s-]+"))) continue;
                if(header==null) { header=cells;continue; }
                String title=field(header,cells,"事项","行动项","行动","任务","工作","title","action","task");
                if(title.isBlank()) continue;
                String code=field(header,cells,"编号","序号","id");
                String owner=field(header,cells,"责任人","负责人","owner");
                String due=field(header,cells,"截止日期","截止时间","截止","due date","due");
                String criteria=field(header,cells,"验收标准","完成标准","验收说明","acceptance criteria");
                put(result,title,code,owner,date(due),criteria,line);
            } else {
                var bullet=BULLET.matcher(line);
                if(bullet.matches()) put(result,bullet.group(1),"","",null,"",line);
            }
        }
        String recommendation=Objects.toString(report.getRecommendationDetail(),"");
        if(recommendation.isBlank()) recommendation=Objects.toString(report.getRecommendation(),"");
        if(result.isEmpty()) for(String line:recommendation.split("\\R")) {
            var bullet=BULLET.matcher(line); if(bullet.matches()) put(result,bullet.group(1),"","",null,"",line);
        }
        return List.copyOf(result.values());
    }
    private static List<String> cells(String line) {
        return Arrays.stream(line.substring(1,line.length()-1).split("(?<!\\\\)\\|",-1)).map(s->s.trim().replace("\\|","|").replace("**","")).toList();
    }
    private static String field(List<String> header,List<String> row,String... names) {
        for(int i=0;i<header.size()&&i<row.size();i++) for(String name:names) if(header.get(i).equalsIgnoreCase(name)) return row.get(i);
        return "";
    }
    private static LocalDate date(String value) {
        var match=Pattern.compile("\\d{4}-\\d{2}-\\d{2}").matcher(value);
        try { return match.find()?LocalDate.parse(match.group()):null; } catch(Exception ignored) { return null; }
    }
    private static void put(Map<String,Draft> result,String title,String code,String owner,LocalDate due,String criteria,String excerpt) {
        title=title.replace("**","").trim(); if(title.isBlank()) return;
        String key=code.matches("[\\w-]{1,40}")?"item:"+code.toLowerCase(Locale.ROOT):"text:"+hash(title).substring(0,40);
        if(result.size()>=100&&!result.containsKey(key)) throw com.cuupe.backend.common.exception.ApiException.badRequest("ACTION_TOO_MANY","报告行动项超过100项，请分批整理报告");
        String description=owner.isBlank()?"来自报告的后续任务":"原文责任人："+owner+"；请指定工作区内的实际负责人。";
        result.putIfAbsent(key,new Draft(key,title,description,criteria.isBlank()?"按来源报告要求完成，并提交可核对的记录。":criteria,owner,due,"HIGH",excerpt));
    }
}
