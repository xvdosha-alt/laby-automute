import net.labymod.labygradle.common.extension.LabyModAnnotationProcessorExtension.ReferenceType

dependencies {
    labyProcessor()
    api(project(":api"))
    api(project(":core"))
    labyApi("core")
}

labyModAnnotationProcessor {
    referenceType = ReferenceType.DEFAULT
}
