package net.llm.autologin.core;

import java.util.Locale;

public final class AuthCommandParser {

    public enum Type {
        LOGIN,
        REGISTER
    }

    public record Parsed(Type type, String password) {
    }

    private AuthCommandParser() {
    }

    public static Parsed parse(String message) {
        if (message == null || message.isBlank()) {
            return null;
        }

        String trimmed = message.trim();
        if (!trimmed.startsWith("/")) {
            return null;
        }

        String[] parts = trimmed.split("\\s+");
        if (parts.length < 2) {
            return null;
        }

        String cmd = parts[0].substring(1).toLowerCase(Locale.ROOT);
        return switch (cmd) {
            case "l", "login" -> parseLogin(parts);
            case "reg", "register" -> parseRegister(parts);
            default -> null;
        };
    }

    private static Parsed parseLogin(String[] parts) {
        if (parts.length < 2) {
            return null;
        }
        String password = parts[1].trim();
        if (password.isEmpty()) {
            return null;
        }
        return new Parsed(Type.LOGIN, password);
    }

    private static Parsed parseRegister(String[] parts) {
        if (parts.length < 3) {
            return null;
        }
        String password = parts[1].trim();
        String confirm = parts[2].trim();
        if (password.isEmpty() || confirm.isEmpty() || !password.equals(confirm)) {
            return null;
        }
        return new Parsed(Type.REGISTER, password);
    }
}
