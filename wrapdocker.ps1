<#
.synopsis
Wrap docker on Windows
.description
Docker can be a little precious sometimes, and Windows is clearly a second class citizen, even today.
.link
https://lmonkiewicz.com/programming/get-noticed-2017/docker-problems-on-windows/
#>
Param(
    [Parameter(Mandatory=$true)] [ValidateSet("buid", "run", "buildrun")] $action,
    $imageName = "psyops",
    $imageTag = "wip"
)

function Invoke-DockerRun {
    $origMsysNoPathconv = $env:MSYS_NO_PATHCONV
    $env:MSYS_NO_PATHCONV = 1
    try {
        docker run --rm -v "${PSScriptRoot}:/psyops:rw" -it "${imageName}:${imageTag}"
        if ($LastExitCode -ne 0) {
            throw "Command 'docker run' exited with nonzero code $LastExitCode"
        }
    } finally {
        $env:MSYS_NO_PATHCONV = $origMsysNoPathconv
    }
}

function Invoke-DockerBuild {
    docker build $PSScriptRoot -t "${imageName}:${imageTag}"
    if ($LastExitCode -ne 0) {
        throw "Command 'docker build' exited with nonzero code $LastExitCode"
    }
}

if ($action -match "build") {
    Invoke-DockerBuild
}
if ($action -match "run") {
    Invoke-DockerRun
}
