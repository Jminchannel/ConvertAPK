plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
}

android {
    namespace = "com.jmin.tubbim"
    compileSdk = 36

    buildFeatures {
        buildConfig = true
    }

    defaultConfig {
        applicationId = "com.jmin.tubbim"
        minSdk = 24
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        // ====== 全局打包变量（模板化）======
        // WebView 首页 URL
        buildConfigField(
            "String",
            "WEBVIEW_URL",
            "\"https://www.google.cn\""
        )
        // 是否隐藏系统状态栏
        buildConfigField("boolean", "HIDE_STATUS_BAR", "false")
        // 状态栏背景： "transparent" 或 "white"
        buildConfigField("String", "STATUS_BAR_BACKGROUND", "\"transparent\"")
        // 状态栏图标风格：true=深色图标（适合白底）；false=浅色图标（适合透明/深色）
        buildConfigField("boolean", "LIGHT_STATUS_BAR_ICONS", "true")
        buildConfigField("boolean", "DOUBLE_CLICK_EXIT", "true")
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
}

dependencies {
//Androidx (Necessary)
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("androidx.browser:browser:1.4.0")
//Admob
//Tramini
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("androidx.webkit:webkit:1.8.0")
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
}
