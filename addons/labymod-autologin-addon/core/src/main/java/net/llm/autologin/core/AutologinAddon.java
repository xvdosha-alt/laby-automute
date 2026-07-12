package net.llm.autologin.core;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.util.HashMap;
import java.util.Map;
import net.labymod.api.addon.LabyAddon;
import net.labymod.api.models.addon.annotation.AddonMain;
import net.llm.autologin.api.LoginBridge;
import net.llm.autologin.api.generated.ReferenceStorage;

@AddonMain
public class AutologinAddon extends LabyAddon<AutologinConfiguration> {

    private static final Gson GSON = new Gson();

    private LoginBridge loginBridge;
    private final PasswordStore passwordStore = new PasswordStore();
    private LoginServer server;
    private volatile int activePort = -1;

    @Override
    protected void enable() {
        ReferenceStorage references = (ReferenceStorage) this.referenceStorageAccessor();
        this.loginBridge = references.loginBridge();
        this.passwordStore.loadFromDisk();
        this.logger().info(
            "Autologin loaded {} password(s) from {}",
            this.passwordStore.size(),
            LoginConfig.resolveAccountsPath()
        );

        this.registerListener(new LoginPromptListener(
            this.loginBridge,
            this.passwordStore,
            line -> this.logger().info(line)
        ));
        this.registerListener(new LoginSendListener(
            this.loginBridge,
            this.passwordStore,
            line -> this.logger().info(line)
        ));

        LoginConfig config = LoginConfig.load();
        this.server = new LoginServer(config, this::handleRequest, port -> {
            this.activePort = port;
            this.logger().info("Autologin listening on {}:{}", config.host(), port);
        });
        this.server.start();
    }

    @Override
    protected Class<AutologinConfiguration> configurationClass() {
        return AutologinConfiguration.class;
    }

    private String handleRequest(String requestLine) {
        JsonObject request;
        try {
            request = JsonParser.parseString(requestLine).getAsJsonObject();
        } catch (Exception e) {
            return error("invalid_json");
        }

        String cmd = getString(request, "cmd");
        if (cmd == null || cmd.isBlank()) {
            return error("missing_cmd");
        }

        return switch (cmd) {
            case "nick" -> handleNick();
            case "status" -> handleStatus();
            case "set_passwords" -> handleSetPasswords(request);
            default -> error("unknown_cmd");
        };
    }

    private String handleNick() {
        String nick = this.loginBridge.getLocalNickname();
        if (nick == null || nick.isBlank()) {
            return error("not_in_world");
        }

        JsonObject response = new JsonObject();
        response.addProperty("ok", true);
        response.addProperty("nick", nick);
        response.addProperty("in_world", this.loginBridge.isInWorld());
        response.addProperty("port", this.activePort);
        return GSON.toJson(response);
    }

    private String handleStatus() {
        JsonObject response = new JsonObject();
        response.addProperty("ok", true);
        response.addProperty("accounts", this.passwordStore.size());
        response.addProperty("port", this.activePort);
        return GSON.toJson(response);
    }

    private String handleSetPasswords(JsonObject request) {
        if (!request.has("accounts") || !request.get("accounts").isJsonArray()) {
            return error("missing_accounts");
        }

        Map<String, String> entries = new HashMap<>();
        JsonArray accounts = request.getAsJsonArray("accounts");
        for (int i = 0; i < accounts.size(); i++) {
            if (!accounts.get(i).isJsonObject()) {
                continue;
            }
            JsonObject item = accounts.get(i).getAsJsonObject();
            String nick = getString(item, "nick");
            String password = getString(item, "password");
            if (nick != null && password != null) {
                entries.put(nick, password);
            }
        }

        if (entries.isEmpty()) {
            return error("empty_accounts");
        }

        this.passwordStore.mergeAll(entries);
        this.logger().info("Autologin passwords merged for {} account(s)", entries.size());

        JsonObject response = new JsonObject();
        response.addProperty("ok", true);
        response.addProperty("accounts", this.passwordStore.size());
        response.addProperty("port", this.activePort);
        return GSON.toJson(response);
    }

    private static String getString(JsonObject object, String key) {
        if (!object.has(key) || object.get(key).isJsonNull()) {
            return null;
        }
        return object.get(key).getAsString();
    }

    private static String error(String message) {
        JsonObject response = new JsonObject();
        response.addProperty("ok", false);
        response.addProperty("error", message);
        return GSON.toJson(response);
    }
}
