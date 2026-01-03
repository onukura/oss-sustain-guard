name := "scala-sample-project"

version := "1.0.0"

scalaVersion := "2.13.12"

libraryDependencies ++= Seq(
  "org.scala-lang" % "scala-library" % "2.13.12",
  "com.typesafe.akka" %% "akka-actor" % "2.8.5",
  "org.scalatest" %% "scalatest" % "3.2.17" % Test
)