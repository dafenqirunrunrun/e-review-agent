package org.linlinjava.litemall.admin.web;

import org.springframework.web.bind.WebDataBinder;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.InitBinder;

import java.beans.PropertyEditorSupport;

@ControllerAdvice(basePackages = "org.linlinjava.litemall.admin.web")
public class AdminRequestParamBinder {
    @InitBinder
    public void initBinder(WebDataBinder binder) {
        binder.registerCustomEditor(Integer.class, new NullableIntegerEditor());
    }

    private static class NullableIntegerEditor extends PropertyEditorSupport {
        @Override
        public void setAsText(String text) {
            if (text == null) {
                setValue(null);
                return;
            }
            String value = text.trim();
            if (value.length() == 0 || "undefined".equalsIgnoreCase(value) || "null".equalsIgnoreCase(value)) {
                setValue(null);
                return;
            }
            setValue(Integer.valueOf(value));
        }
    }
}
