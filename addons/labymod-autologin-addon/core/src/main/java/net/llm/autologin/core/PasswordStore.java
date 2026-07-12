package net.llm.autologin.core;

import java.util.Locale;
import java.util.Map;
import java.nio.file.Path;
import java.util.concurrent.ConcurrentHashMap;

public final class PasswordStore {

    private final AccountsFileStore fileStore;
    private final Map<String, StoredAccount> accounts = new ConcurrentHashMap<>();

    public PasswordStore() {
        this(new AccountsFileStore());
    }

    PasswordStore(AccountsFileStore fileStore) {
        this.fileStore = fileStore;
    }

    public void loadFromDisk() {
        this.accounts.clear();
        this.accounts.putAll(this.fileStore.load());
        if (this.accounts.isEmpty()) {
            Path legacyPath = legacyAccountsPath();
            if (legacyPath != null) {
                AccountsFileStore legacyStore = new AccountsFileStore(legacyPath);
                Map<String, StoredAccount> legacy = legacyStore.load();
                if (!legacy.isEmpty()) {
                    this.accounts.putAll(legacy);
                    this.fileStore.save(this.accounts);
                }
            }
        }
    }

    private static Path legacyAccountsPath() {
        String appData = System.getenv("APPDATA");
        if (appData == null || appData.isBlank()) {
            return null;
        }
        return Path.of(appData, ".minecraft", "config", "autologin", "accounts.json");
    }

    public void mergeAll(Map<String, String> entries) {
        for (Map.Entry<String, String> entry : entries.entrySet()) {
            String key = entry.getKey().toLowerCase(Locale.ROOT);
            if (this.accounts.containsKey(key)) {
                continue;
            }
            put(entry.getKey(), entry.getValue());
        }
    }

    public void put(String nick, String password) {
        put(nick, password, "");
    }

    public void put(String nick, String password, String serverAddress) {
        if (nick == null || nick.isBlank() || password == null || password.isBlank()) {
            return;
        }
        String key = nick.toLowerCase(Locale.ROOT);
        String server = serverAddress == null ? "" : serverAddress.trim();
        this.accounts.put(key, new StoredAccount(password, server));
        this.fileStore.save(this.accounts);
    }

    public String getPassword(String nick, String serverAddress) {
        if (nick == null || nick.isBlank()) {
            return null;
        }

        StoredAccount account = this.accounts.get(nick.toLowerCase(Locale.ROOT));
        if (account == null || account.password() == null || account.password().isBlank()) {
            return null;
        }

        if (!AutologinServerFilter.serversMatch(account.server(), serverAddress)) {
            return null;
        }

        return account.password();
    }

    public int size() {
        return this.accounts.size();
    }
}
