plugins {
    id("net.labymod.labygradle")
    id("net.labymod.labygradle.addon")
}

val versions = providers.gradleProperty("net.labymod.minecraft-versions").get().split(";")

group = "net.llm"
version = providers.environmentVariable("VERSION").getOrElse("1.0.0")

labyMod {
    defaultPackageName = "net.llm.chatcopy"

    minecraft {
        registerVersion(versions.toTypedArray()) {
            runs {
                getByName("client") {
                }
            }
        }
    }

    addonInfo {
        namespace = "chatcopy"
        displayName = "Chat Copy"
        author = "llm"
        description = "Adds a [copy] button after each chat message"
        minecraftVersion = "1.20.1"
        version = rootProject.version.toString()
    }
}

subprojects {
    plugins.apply("net.labymod.labygradle")
    plugins.apply("net.labymod.labygradle.addon")

    group = rootProject.group
    version = rootProject.version

    extensions.findByType(JavaPluginExtension::class.java)?.apply {
        sourceCompatibility = JavaVersion.VERSION_21
        targetCompatibility = JavaVersion.VERSION_21
    }
}
