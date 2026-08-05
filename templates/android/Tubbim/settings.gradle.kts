pluginManagement {
    repositories {
        flatDir {
            dirs("libs")
        }
        //TU(Core)
        maven {
            url = uri("https://jfrog.anythinktech.com/artifactory/overseas_sdk")  // 添加这行
        }

        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        flatDir {
            dirs("libs")  // 添加这行
        }
        //TU(Core)
        maven {
            url = uri("https://jfrog.anythinktech.com/artifactory/overseas_sdk")  // 添加这行
        }
        google()
        mavenCentral()
    }
}

rootProject.name = "Tubbim"
include(":app")
 