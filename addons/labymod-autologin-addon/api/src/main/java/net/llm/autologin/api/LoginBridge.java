package net.llm.autologin.api;

import net.labymod.api.reference.annotation.Referenceable;

@Referenceable
public interface LoginBridge {

    String getLocalNickname();

    boolean isInWorld();

    String getServerAddress();

    void sendChat(String message) throws Exception;
}
