package org.linlinjava.litemall.core.validator;

import com.google.common.collect.Lists;

import javax.validation.ConstraintValidator;
import javax.validation.ConstraintValidatorContext;
import java.util.List;

public class SortValidator implements ConstraintValidator<Sort, String> {
    private List<String> valueList;

    @Override
    public void initialize(Sort sort) {
        valueList = Lists.newArrayList();
        for (String val : sort.accepts()) {
            valueList.add(val.toUpperCase());
        }
    }

    @Override
    public boolean isValid(String s, ConstraintValidatorContext constraintValidatorContext) {
        if (s == null) {
            return true;
        }
        String value = s.trim();
        if (value.length() == 0 || "undefined".equalsIgnoreCase(value) || "null".equalsIgnoreCase(value)) {
            return true;
        }
        if (!valueList.contains(value.toUpperCase())) {
            return false;
        }
        return true;
    }
}
