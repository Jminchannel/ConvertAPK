!include "LogicLib.nsh"
!include "nsDialogs.nsh"

!ifndef BUILD_UNINSTALLER
  Var DataRoot
  Var DataRootInput
  Var DataRootBrowse

  !macro customPageAfterChangeDir
    Page custom DataRootPageCreate DataRootPageLeave
  !macroend

  Function DataRootPageCreate
    nsDialogs::Create 1018
    Pop $0
    ${If} $0 == error
      Abort
    ${EndIf}

    ${If} $DataRoot == ""
      StrCpy $DataRoot "$LOCALAPPDATA\ConvertAPK"
    ${EndIf}

    ${NSD_CreateLabel} 0u 0u 100% 12u "构建数据目录"
    Pop $1
    ${NSD_CreateLabel} 0u 16u 100% 24u "用于存放构建缓存/输出文件。建议路径全英文（字母/数字），避免其他字符。"
    Pop $1
    ${NSD_CreateText} 0u 44u 75% 12u "$DataRoot"
    Pop $DataRootInput
    ${NSD_CreateButton} 78% 43u 22% 14u "浏览..."
    Pop $DataRootBrowse
    ${NSD_OnClick} $DataRootBrowse DataRootBrowseClicked

    nsDialogs::Show
  FunctionEnd

  Function DataRootBrowseClicked
    ${NSD_GetText} $DataRootInput $0
    nsDialogs::SelectFolderDialog "选择构建数据目录" "$0"
    Pop $1
    ${If} $1 != "error"
      ${NSD_SetText} $DataRootInput $1
    ${EndIf}
  FunctionEnd

  Function DataRootPageLeave
    ${NSD_GetText} $DataRootInput $DataRoot
  FunctionEnd
!endif

!macro customInstall
  ; Prompt for data storage directory and write it into config.json.
  StrCpy $0 "$LOCALAPPDATA\ConvertAPK"
  ${If} $DataRoot != ""
    StrCpy $0 $DataRoot
  ${EndIf}
  CreateDirectory "$0"
  CreateDirectory "$APPDATA\ConvertAPK"
  StrCpy $2 ""
  StrLen $3 $0
  StrCpy $4 0
  ConvertAPK_PathLoop:
    IntCmp $4 $3 ConvertAPK_PathDone
    StrCpy $5 $0 1 $4
    StrCmp $5 "\" 0 +2
      StrCpy $5 "/"
    StrCpy $2 "$2$5"
    IntOp $4 $4 + 1
    Goto ConvertAPK_PathLoop
  ConvertAPK_PathDone:
  FileOpen $3 "$APPDATA\ConvertAPK\config.json" w
  FileWrite $3 "{$\r$\n"
  FileWrite $3 "  $\"data_root$\": $\"$2$\"$\r$\n"
  FileWrite $3 "}$\r$\n"
  FileClose $3
!macroend

!macro customUnInstall
  ; Ensure running app exits before uninstall continues.
  nsExec::ExecToLog 'taskkill /F /T /IM "ConvertAPK.exe"'
  nsExec::ExecToLog 'taskkill /F /T /IM "ConvertAPK_backend.exe"'
  nsExec::ExecToLog 'taskkill /F /T /IM "ConvertAPK-backend.exe"'
  ; Remove shortcuts (both per-user and per-machine).
  Delete "$DESKTOP\ConvertAPK.lnk"
  Delete "$SMPROGRAMS\ConvertAPK\ConvertAPK.lnk"
  Delete "$SMPROGRAMS\ConvertAPK\Uninstall ConvertAPK.lnk"
  RMDir "$SMPROGRAMS\ConvertAPK"
  ; Remove per-user data and cached toolchain for a clean uninstall.
  RMDir /r "$APPDATA\ConvertAPK"
  RMDir /r "$LOCALAPPDATA\ConvertAPK"
  RMDir /r "$LOCALAPPDATA\Programs\ConvertAPK"
  ; Remove install directory contents.
  RMDir /r "$INSTDIR"
!macroend
