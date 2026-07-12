package net.llm.autologin.core;

import java.util.function.Consumer;
import net.labymod.api.event.Subscribe;
import net.labymod.api.event.client.chat.ChatMessageSendEvent;
import net.llm.autologin.api.LoginBridge;

public class LoginSendListener {

    private final LoginBridge loginBridge;
    private final PasswordStore passwordStore;
    private final Consumer<String> logger;

    public LoginSendListener(
        LoginBridge loginBridge,
        PasswordStore passwordStore,
        Consumer<String> logger
    ) {
        this.loginBridge = loginBridge;
        this.passwordStore = passwordStore;
        this.logger = logger;
    }

    @Subscribe
    public void onChatSend(ChatMessageSendEvent event) {
        if (!this.loginBridge.isInWorld()) {
            return;
        }

        String serverAddress = this.loginBridge.getServerAddress();
        if (!AutologinServerFilter.isAllowed(serverAddress)) {
            return;
        }

        AuthCommandParser.Parsed parsed = AuthCommandParser.parse(event.getMessage());
        if (parsed == null) {
            return;
        }

        String nick = this.loginBridge.getLocalNickname();
        if (nick == null || nick.isBlank()) {
            return;
        }

        this.passwordStore.put(nick, parsed.password(), serverAddress);
        this.logger.accept(
            "[autologin] запомнил "
                + (parsed.type() == AuthCommandParser.Type.REGISTER ? "/reg" : "/l")
                + " для "
                + nick
                + " ("
                + AutologinServerFilter.serverKey(serverAddress)
                + ")"
        );
    }
}
