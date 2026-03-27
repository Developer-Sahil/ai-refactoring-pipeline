<?php

interface MailService {
    public function send($to, $subject);
}

class Mailer implements MailService {
    public function send($to, $subject) {
        return true;
    }
}
