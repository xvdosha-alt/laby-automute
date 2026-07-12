package net.llm.screenshotbridge.api;

import java.util.List;
import net.labymod.api.reference.annotation.Referenceable;

@Referenceable
public interface BridgePlayer {

    String getLocalNickname();

    boolean isInWorld();

    void sendChat(String message) throws Exception;

    List<String> getOnlinePlayerNicks() throws Exception;

    boolean hasAlteredNickDisplay(String nick);

    AutoLoginResult runAutoLogin() throws Exception;
}
