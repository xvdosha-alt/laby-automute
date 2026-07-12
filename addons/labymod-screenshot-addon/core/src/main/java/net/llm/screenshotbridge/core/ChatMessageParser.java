package net.llm.screenshotbridge.core;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class ChatMessageParser {

    private static final Pattern CONTENT = Pattern.compile(
        "(?:[^\\|│┃\\u2502\\u2503]+[\\|│┃\\u2502\\u2503]\\s+)?"
            + "(?:«[^»]*»\\s+)?(~)?([A-Za-z0-9_]{2,16})(?:\\s+[^:]+)?:\\s*(.+)$"
    );

    private static final Pattern SENDER_SUFFIX = Pattern.compile(
        "(~)?([A-Za-z0-9_]{2,16}):\\s*(.+)$"
    );

    private ChatMessageParser() {
    }

    public static ParsedMessage parse(String raw) {
        if (raw == null || raw.isBlank()) {
            return null;
        }

        String trimmed = raw.trim();
        Matcher matcher = CONTENT.matcher(trimmed);
        if (matcher.find()) {
            boolean altered = matcher.group(1) != null;
            return toParsed(matcher.group(2), matcher.group(3), altered);
        }

        matcher = SENDER_SUFFIX.matcher(trimmed);
        if (matcher.find()) {
            boolean altered = matcher.group(1) != null;
            return toParsed(matcher.group(2), matcher.group(3), altered);
        }

        return null;
    }

    public static ParsedMessage parseWithSender(String raw, String senderNick) {
        if (senderNick != null && senderNick.startsWith("~")) {
            return null;
        }

        ParsedMessage parsed = parse(raw);
        if (parsed != null) {
            if (!parsed.alteredNick() && raw != null && hasAlteredNickPrefix(raw, parsed.nickname())) {
                return new ParsedMessage(parsed.nickname(), parsed.text(), true);
            }
            return parsed;
        }
        if (senderNick == null || senderNick.isBlank() || senderNick.contains("~")) {
            return null;
        }
        if (raw == null || raw.isBlank()) {
            return null;
        }

        String trimmed = raw.trim();
        if (hasAlteredNickPrefix(trimmed, senderNick)) {
            return null;
        }

        Pattern nickPattern = Pattern.compile(
            Pattern.quote(senderNick) + ":\\s*(.+)$",
            Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE
        );
        Matcher matcher = nickPattern.matcher(trimmed);
        if (matcher.find()) {
            String text = matcher.group(1).trim();
            if (!text.isBlank()) {
                return new ParsedMessage(senderNick, text, false);
            }
        }

        return null;
    }

    public static boolean hasAlteredNickPrefix(String raw, String nickname) {
        if (raw == null || raw.isBlank() || nickname == null || nickname.isBlank()) {
            return false;
        }
        Pattern pattern = Pattern.compile(
            "(?:^|[^\\w])~" + Pattern.quote(nickname.trim()) + "\\s*:",
            Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE
        );
        return pattern.matcher(raw.trim()).find();
    }

    private static ParsedMessage toParsed(String nickname, String text, boolean alteredNick) {
        if (nickname == null || text == null || nickname.contains("~")) {
            return null;
        }
        String nick = nickname.trim();
        if (isInvalidNickname(nick)) {
            return null;
        }
        String message = text.trim();
        if (message.isBlank()) {
            return null;
        }
        return new ParsedMessage(nick, message, alteredNick);
    }

    private static boolean isInvalidNickname(String nickname) {
        String low = nickname.toLowerCase(java.util.Locale.ROOT);
        return low.equals("http") || low.equals("https") || low.equals("ftp") || low.equals("www");
    }

    public record ParsedMessage(String nickname, String text, boolean alteredNick) {
    }
}
