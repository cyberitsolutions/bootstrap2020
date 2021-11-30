Method (not scriptable due to js bullshit):

#. Browse to https://chromeenterprise.google/policies/
#. Allow all js.
#. Check "Include deprecated policies".
#. Change "Any Platform" to "Linux".
#. For each version (except "beta"),

   #. Choose that version (e.g. "Chrome 94").
   #. File > Save Page As > "94.html".
   #. w3m -dump 94.html >94.txt
   #. git diff --no-index -U0 93.txt 94.txt >93-94.diff
   #. Manually post-process the .diff into useful format.

Since very old versions are hidden from the drop-down,
this process has to be done at least once every 3-5 years, or
there will be gaps!


Linux Chromium Policy Changes
=============================

Chromium 87::

    Miscellaneous
    +  • MediaRecommendationsEnabled
    +  • WebRtcAllowLegacyTLSProtocols

Chromium 88::

    Content settings
    -  • DefaultPluginsSetting (deprecated)
    +  • DefaultSensorsSetting
    -  • PluginsAllowedForUrls (deprecated)
    -  • PluginsBlockedForUrls (deprecated)
    +  • SensorsAllowedForUrls
    +  • SensorsBlockedForUrls
    HTTP authentication
    +  • BasicAuthOverHttpEnabled
    Miscellaneous
    -  • AllowOutdatedPlugins (deprecated)
    -  • AllowPopupsDuringPageUnload (deprecated)
    -  • DisabledPlugins (deprecated)
    -  • DisabledPluginsExceptions (deprecated)
    -  • EnableDeprecatedWebPlatformFeatures (deprecated)
    -  • EnabledPlugins (deprecated)
    -  • ForceLegacyDefaultReferrerPolicy (deprecated)
    +  • IntranetRedirectBehavior
    -  • LocalDiscoveryEnabled (deprecated)
    +  • NTPCardsVisible
    +  • TargetBlankImpliesNoOpener
    Printing
    -  • CloudPrintWarningsSuppressed (deprecated)

Chromium 89::

    Miscellaneous
    +  • BrowserLabsEnabled
    +  • BrowsingDataLifetime
    +  • ClearBrowsingDataOnExitList
    +  • EnableDeprecatedPrivetPrinting (deprecated)
    +  • ManagedConfigurationPerOrigin
    +  • ProfilePickerOnStartupAvailability
    -  • RunAllFlashInAllowMode (deprecated)
    +  • SigninInterceptionEnabled
    Remote access
    +  • RemoteAccessHostAllowRemoteAccessConnections
    +  • RemoteAccessHostMaximumSessionDurationMinutes

Chromium 90::

    Miscellaneous
    +  • AllowSystemNotifications
    +  • FetchKeepaliveDurationSecondsOnShutdown
    +  • SSLErrorOverrideAllowedForOrigins

Chromium 91::

    Content settings
    +  • DefaultFileHandlingGuardSetting (deprecated)
    +  • FileHandlingAllowedForUrls (deprecated)
    +  • FileHandlingBlockedForUrls (deprecated)
    Miscellaneous
    +  • BrowserThemeColor
    +  • CECPQ2Enabled
    +  • ExplicitlyAllowedNetworkPorts
    +  • ForcedLanguages
    +  • HeadlessMode
    +  • LacrosSecondaryProfilesAllowed
    +  • SharedArrayBufferUnrestrictedAccessAllowed
    +  • SuppressDifferentOriginSubframeDialogs
    +  • WebRtcIPHandling

Chromium 92::

    Miscellaneous
    +  • AdditionalDnsQueryTypesEnabled
    +  • CloudUserPolicyMerge
    +  • InsecurePrivateNetworkRequestsAllowed
    +  • InsecurePrivateNetworkRequestsAllowedForUrls
    +  • TripleDESEnabled (deprecated)

Chromium 93::

    Content settings
    +  • DefaultJavaScriptJitSetting
    -  • LegacySameSiteCookieBehaviorEnabled (deprecated)
    +  • JavaScriptJitAllowedForSites
    +  • JavaScriptJitBlockedForSites
    Miscellaneous
    +  • DesktopSharingHubEnabled
    +  • LockIconInAddressBarEnabled
    +  • RelaunchWindow
    +  • RemoteDebuggingAllowed

Chromium 94::

    Allow or deny screen capture
    +  • SameOriginTabCaptureAllowedByOrigins
    +  • ScreenCaptureAllowedByOrigins
    +  • TabCaptureAllowedByOrigins
    +  • WindowCaptureAllowedByOrigins
    Content settings
    +  • SerialAllowAllPortsForUrls
    +  • SerialAllowUsbDevicesForUrls
    Miscellaneous
    +  • CrossOriginWebAssemblyModuleSharingEnabled
    +  • DisplayCapturePermissionsPolicyEnabled
    -  • EnableDeprecatedPrivetPrinting (deprecated)
    +  • HttpsOnlyMode
    +  • LensRegionSearchEnabled
    +  • ManagedAccountsSigninRestriction
    -  • UserAgentClientHintsEnabled (deprecated)
    Printing
    +  • PrintRasterizePdfDpi

Chromium 95::

    Legacy Browser Support
    +  • BrowserSwitcherParsingMode
    Miscellaneous
    +  • ContextAwareAccessSignalsAllowlist
    Printing
    +  • PrintPdfAsImageDefault

Chromium 96::

    Miscellaneous
    -  • AppCacheForceEnabled (deprecated)
    +  • CloudUserPolicyOverridesCloudMachinePolicy
    +  • PromptOnMultipleMatchingCertificates
    +  • SandboxExternalProtocolBlocked
    +  • U2fSecurityKeyApiEnabled
    +  • WebSQLInThirdPartyContextEnabled
