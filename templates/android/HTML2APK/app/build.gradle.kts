plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "osa.cosa.html2apk"
    compileSdk {
        version = release(36)
    }

    defaultConfig {
        applicationId = "osa.cosa.html2apk"
        minSdk = 24
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        buildConfigField("boolean", "HIDE_STATUS_BAR", "false")
        buildConfigField("String", "STATUS_BAR_BACKGROUND", "\"transparent\"")
        buildConfigField("boolean", "LIGHT_STATUS_BAR_ICONS", "false")
        buildConfigField("boolean", "DOUBLE_CLICK_EXIT", "true")
        buildConfigField("String", "SCREEN_ORIENTATION", "\"auto\"")
        buildConfigField("String", "DOWNLOAD_MODE", "\"picker\"")
        buildConfigField("String", "WEB_FILL_MODE", "\"contain\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    kotlinOptions {
        jvmTarget = "11"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }

    sourceSets {
        getByName("main") {
            assets.srcDir(layout.buildDirectory.dir("generated/htmlAssets"))
        }
    }
}

val syncHtmlAssets by tasks.registering(org.gradle.api.tasks.Sync::class) {
    from(rootProject.layout.projectDirectory.dir("html2apkdemo"))
    into(layout.buildDirectory.dir("generated/htmlAssets/html2apkdemo"))
}

tasks.named("preBuild") {
    dependsOn(syncHtmlAssets)
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    debugImplementation(libs.androidx.compose.ui.tooling)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
}
