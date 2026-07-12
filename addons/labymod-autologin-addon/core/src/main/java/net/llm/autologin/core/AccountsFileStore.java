package net.llm.autologin.core;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

public final class AccountsFileStore {

    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    private final Path storePath;

    public AccountsFileStore() {
        this(LoginConfig.resolveAccountsPath());
    }

    AccountsFileStore(Path storePath) {
        this.storePath = storePath;
    }

    public Path storePath() {
        return this.storePath;
    }

    public Map<String, StoredAccount> load() {
        if (!Files.exists(this.storePath)) {
            return new HashMap<>();
        }

        try {
            String json = Files.readString(this.storePath);
            JsonObject object = JsonParser.parseString(json).getAsJsonObject();
            Map<String, StoredAccount> accounts = new HashMap<>();
            for (Map.Entry<String, JsonElement> entry : object.entrySet()) {
                String nick = entry.getKey();
                if (nick == null || nick.isBlank()) {
                    continue;
                }

                JsonElement value = entry.getValue();
                if (value.isJsonPrimitive()) {
                    String password = value.getAsString();
                    if (password != null && !password.isBlank()) {
                        accounts.put(
                            nick.toLowerCase(Locale.ROOT),
                            new StoredAccount(password, "")
                        );
                    }
                    continue;
                }

                if (!value.isJsonObject()) {
                    continue;
                }

                JsonObject item = value.getAsJsonObject();
                String password = getString(item, "password");
                if (password == null || password.isBlank()) {
                    continue;
                }
                String server = getString(item, "server");
                accounts.put(
                    nick.toLowerCase(Locale.ROOT),
                    new StoredAccount(password, server == null ? "" : server)
                );
            }
            return accounts;
        } catch (Exception ignored) {
            return new HashMap<>();
        }
    }

    public void save(Map<String, StoredAccount> accounts) {
        try {
            Files.createDirectories(this.storePath.getParent());
            JsonObject object = new JsonObject();
            for (Map.Entry<String, StoredAccount> entry : accounts.entrySet()) {
                JsonObject item = new JsonObject();
                item.addProperty("password", entry.getValue().password());
                item.addProperty("server", entry.getValue().server());
                object.add(entry.getKey(), item);
            }
            Files.writeString(this.storePath, GSON.toJson(object));
        } catch (IOException ignored) {
        }
    }

    private static String getString(JsonObject object, String key) {
        if (!object.has(key) || object.get(key).isJsonNull()) {
            return null;
        }
        return object.get(key).getAsString();
    }
}
