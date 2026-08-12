package com.cuupe.backend.common;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class Result<T> {
    private String code;
    private String message;
    private T data;

    /**
     * 创建成功响应（带自定义code和message）
     * @param code 响应码
     * @param message 响应消息
     * @param data 响应数据
     * @return 成功响应对象
     */
    public static <T> Result<T> success(String code, String message, T data){
        return new Result<>(code, message, data);
    }
    /**
     * 创建成功响应（带数据）
     * @param data 响应数据
     * @return 成功响应对象
     */
    public static <T> Result<T> success(T data){
        return new Result<>("SUCCESS", "success", data);
    }
    /**
     * 创建成功响应（无数据）
     * @return 成功响应对象
     */
    public static Result<Void> success(){
        return new Result<>("SUCCESS","success", null);
    }
    /**
     * 创建失败响应
     * @param code 错误码
     * @param message 错误消息
     * @return 失败响应对象
     */
    public static <T> Result<T> fail(String code, String message){
        return new Result<>(code, message, null);
    }
}