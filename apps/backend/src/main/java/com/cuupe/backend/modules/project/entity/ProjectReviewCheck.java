package com.cuupe.backend.modules.project.entity;

import java.util.List;

/** Public checks distinguish machine-verifiable gaps from human judgement. */
public record ProjectReviewCheck(String key, String title, String status, String detail,
                                 String route, List<String> excerpts) {}
