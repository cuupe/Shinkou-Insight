package com.cuupe.backend.utils;

import java.util.List;
import java.util.Random;

public class RandomUtil {
    public static int RandomInt(){
        Random random = new Random();
        return random.nextInt();
    }

    public static int RandomInt(int end){
        Random random = new Random();
        return random.nextInt(end);
    }

    public static int RandomInt(int start, int end){
        Random random = new Random();
        return random.nextInt(start, end);
    }

    public static int[] RandomIntSequence(int length){
        Random random = new Random();
        int[] arr = new int[length];
        for(int i : arr){
            i = random.nextInt();
        }

        return arr;
    }

    public static String RandomIntSequenceSingle(int length){
        Random random = new Random();
        StringBuilder sb = new StringBuilder();
        while(length-- > 0){
            sb.append(Integer.toString(random.nextInt(10)));
        }

        return sb.toString();
    }
}
