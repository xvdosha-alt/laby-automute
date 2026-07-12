package net.llm.screenshotbridge.core;

import java.util.function.Consumer;
import net.labymod.api.client.chat.command.Command;
import net.llm.screenshotbridge.api.AutoLoginResult;
import net.llm.screenshotbridge.api.BridgePlayer;

public class MlCommand extends Command {

    private final BridgePlayer bridgePlayer;
    private final Consumer<String> logger;

    public MlCommand(BridgePlayer bridgePlayer, Consumer<String> logger) {
        super("ml");
        this.bridgePlayer = bridgePlayer;
        this.logger = logger;
    }

    @Override
    public boolean execute(String prefix, String[] arguments) {
        Thread worker = new Thread(() -> {
            try {
                AutoLoginResult result = this.bridgePlayer.runAutoLogin();
                AutoLoginSupport.logResult(result, this.logger);
            } catch (Exception e) {
                this.logger.accept("[ml] ошибка: " + e.getMessage());
            }
        }, "ml-autologin");
        worker.setDaemon(true);
        worker.start();
        return true;
    }
}
