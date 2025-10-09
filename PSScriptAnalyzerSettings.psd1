# PowerShell Script Analyzer Settings para CLIP Comparador V2
# Este archivo desactiva el análisis de scripts PowerShell

@{
    # Deshabilitar todas las reglas de análisis
    ExcludeRules = @(
        'PSAvoidUsingCmdletAliases',
        'PSAvoidUsingPlainTextForPassword', 
        'PSAvoidUsingConvertToSecureStringWithPlainText',
        'PSAvoidUsingUserNameAndPasswordParams',
        'PSAvoidUsingPositionalParameters',
        'PSUseDeclaredVarsMoreThanAssignments',
        'PSUseSingularNouns',
        'PSUseApprovedVerbs',
        'PSUseShouldProcessForStateChangingFunctions',
        'PSAvoidGlobalVars',
        'PSAvoidUsingInvokeExpression',
        'PSUseCmdletCorrectly',
        'PSAvoidTrailingWhitespace'
    )
    
    # Incluir solo archivos específicos (ninguno para desactivar completamente)
    IncludeRules = @()
    
    # Severidad mínima para reportar problemas (None para desactivar)
    Severity = @()
}
