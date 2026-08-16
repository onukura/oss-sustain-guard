plugins {
    scala
}

repositories {
    mavenCentral()
}

dependencies {
    implementation("org.scala-lang:scala-library:2.13.12")
    implementation("com.typesafe.akka:akka-actor_2.13:2.8.5")
    testImplementation("org.scalatest:scalatest_2.13:3.2.17")
}

