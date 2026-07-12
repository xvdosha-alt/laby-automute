package net.llm.autologin.core;

import java.util.Locale;
import java.util.function.Consumer;
import net.labymod.api.event.Subscribe;
import net.labymod.api.event.client.chat.ChatReceiveEvent;
import net.llm.autologin.api.LoginBridge;

public class LoginPromptListener {

    private static final long RESEND_COOLDOWN_MS = 5_000;

    private final LoginBridge loginBridge;
    private final PasswordStore passwordStore;
    private final Consumer<String> logger;
    private volatile long lastAuthAt;
    private volatile String lastSentPassword = "";

    public LoginPromptListener(
        LoginBridge loginBridge,
        PasswordStore passwordStore,
        Consumer<String> logger
    ) {
        this.loginBridge = loginBridge;
        this.passwordStore = passwordStore;
        this.logger = logger;
    }

    @Subscribe
    public void onChatReceive(ChatReceiveEvent event) {
        if (!this.loginBridge.isInWorld()) {
            return;
        }

        String serverAddress = this.loginBridge.getServerAddress();
        if (!AutologinServerFilter.isAllowed(serverAddress)) {
            return;
        }

        String text = event.chatMessage().getPlainText();
        PromptType promptType = detectPromptType(text);
        if (promptType == null) {
            return;
        }

        String nick = this.loginBridge.getLocalNickname();
        if (nick == null || nick.isBlank()) {
            return;
        }

        String password = this.passwordStore.getPassword(nick, serverAddress);
        if (password == null) {
            this.logger.accept(
                "[autologin] нет пароля для "
                    + nick
                    + " на "
                    + AutologinServerFilter.serverKey(serverAddress)
            );
            return;
        }

        long now = System.currentTimeMillis();
        if (
            now - this.lastAuthAt < RESEND_COOLDOWN_MS
                && password.equals(this.lastSentPassword)
        ) {
            return;
        }
        this.lastAuthAt = now;
        this.lastSentPassword = password;

        String command = promptType == PromptType.REGISTER
            ? "/reg " + password + " " + password
            : "/l " + password;

        Thread worker = new Thread(() -> {
            try {
                this.logger.accept(
                    promptType == PromptType.REGISTER
                        ? "[autologin] /reg для " + nick
                        : "[autologin] /l для " + nick
                );
                this.loginBridge.sendChat(command);
            } catch (Exception e) {
                this.logger.accept("[autologin] ошибка: " + e.getMessage());
            }
        }, "autologin-send");
        worker.setDaemon(true);
        worker.start();
    }

    private enum PromptType {
        LOGIN,
        REGISTER
    }

    static PromptType detectPromptType(String text) {
        if (text == null || text.isBlank()) {
            return null;
        }

        String lower = text.toLowerCase(Locale.ROOT);
        if (isRegisterPrompt(lower)) {
            return PromptType.REGISTER;
        }
        if (isLoginPrompt(lower)) {
            return PromptType.LOGIN;
        }
        return null;
    }

    static boolean isLoginPrompt(String lower) {
        if (!hasPasswordPlaceholder(lower)) {
            return false;
        }
        return mentionsLoginCommand(lower);
    }

    static boolean isRegisterPrompt(String lower) {
        if (!hasPasswordPlaceholder(lower)) {
            return false;
        }
        return mentionsRegisterCommand(lower);
    }

    static boolean mentionsLoginCommand(String lower) {
        if (lower.contains("/login")) {
            return true;
        }
        return containsStandaloneCommand(lower, "/l");
    }

    static boolean mentionsRegisterCommand(String lower) {
        if (lower.contains("/register")) {
            return true;
        }
        return containsStandaloneCommand(lower, "/reg");
    }

    private static boolean containsStandaloneCommand(String lower, String command) {
        int index = lower.indexOf(command);
        while (index >= 0) {
            int after = index + command.length();
            if (after >= lower.length() || !Character.isLetterOrDigit(lower.charAt(after))) {
                return true;
            }
            index = lower.indexOf(command, after);
        }
        return false;
    }

    private static boolean hasPasswordPlaceholder(String lower) {
        return lower.contains("[пароль]")
            || lower.contains("[password]")
            || lower.contains("<password>")
            || lower.contains("<пароль>");
    }
}
