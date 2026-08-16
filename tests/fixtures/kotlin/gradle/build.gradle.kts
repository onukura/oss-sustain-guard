plugins {
    kotlin("jvm") version "1.9.22"
}

repositories {
    mavenCentral()
}

dependencies {
    implementation("org.jetbrains.kotlin:kotlin-stdlib:1.9.22")
    implementation("io.ktor:ktor-server-core:2.3.7")
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.1")
}

