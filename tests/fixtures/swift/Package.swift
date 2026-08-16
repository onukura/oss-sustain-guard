// swift-tools-version:5.7
import PackageDescription

let package = Package(
    name: "Example",
    dependencies: [
        .package(url: "https://github.com/apple/swift-nio.git", from: "2.56.0"),
        .package(url: "https://github.com/Alamofire/Alamofire.git", from: "5.8.0")
    ]
)
