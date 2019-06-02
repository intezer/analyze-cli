library 'common'

pipeline {
    agent {
        label 'slave-ssd'
     }

    options {
        timestamps()
        timeout(time: 20, unit: 'MINUTES')
    }

    stages {
        stage('Notify') {
            steps {
                slackSend channel: "#jenkins", message: "Build Started - ${env.JOB_NAME} ${env.BUILD_NUMBER} (<${env.BUILD_URL}|Open>)"
            }
        }
        stage('Cleanup') {
            steps {
                sh 'rm -f tests/**/results*.xml'
            }
        }
        stage('Tests') {
            steps {
                sh 'docker-compose up --build'
                junit 'tests/**/results*.xml'
            }
            post {
                always {
                    script {
                        env.JUNIT_RESULT_TEXT = junitResultExtractor()
                    }
                }
                success {
                    slackSend channel: "#jenkins", color: "good", message: "${env.JOB_NAME}-#${env.BUILD_NUMBER} Build succeeded: ${env.JUNIT_RESULT_TEXT}"
                }
                failure {
                    slackSend channel: "#jenkins", color: "danger", message: "${env.JOB_NAME}-#${env.BUILD_NUMBER} Build failed (<${env.BUILD_URL}|Open>): ${env.JUNIT_RESULT_TEXT}"
                }
                unstable {
                    slackSend channel: "#jenkins", color: "warning", message: "${env.JOB_NAME}-#${env.BUILD_NUMBER} Build unstable (<${env.BUILD_URL}|Open>): ${env.JUNIT_RESULT_TEXT}"
                }
            }
        }
        stage('Deploy') {
            when {
                branch "master"
            }
            steps {
                sh 'docker run --rm -v $(pwd):/code intezer/python-setuptools sh /build-and-upload-public-pypi.sh'
            }
        }
    }
}
