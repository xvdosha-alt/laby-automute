package net.llm.autologin.core;

import java.util.Locale;

public final class AutologinServerFilter {

    private static final String HOLYWORLD_MARKER = "holyworld";

    private AutologinServerFilter() {
    }

    public static boolean isAllowed(String serverAddress) {
        return serverAddress != null && !serverAddress.isBlank();
    }

    public static String serverKey(String serverAddress) {
        if (serverAddress == null || serverAddress.isBlank()) {
            return "";
        }
        String lower = serverAddress.toLowerCase(Locale.ROOT).trim();
        if (lower.contains(HOLYWORLD_MARKER)) {
            return HOLYWORLD_MARKER;
        }
        int colon = lower.indexOf(':');
        if (colon >= 0) {
            lower = lower.substring(0, colon);
        }
        return lower.trim();
    }

    public static boolean serversMatch(String storedAddress, String currentAddress) {
        if (!isAllowed(currentAddress)) {
            return false;
        }
        if (storedAddress == null || storedAddress.isBlank()) {
            return true;
        }
        String storedKey = serverKey(storedAddress);
        String currentKey = serverKey(currentAddress);
        return !storedKey.isBlank() && storedKey.equals(currentKey);
    }
}
