import 'dart:io';

String get _commandFile => '${Directory.systemTemp.path}/flutter_pi_command';

void sendCommand(String command) {
  File(_commandFile).writeAsStringSync(command);
}

String? readAndClearCommand() {
  final file = File(_commandFile);
  if (!file.existsSync()) return null;
  final cmd = file.readAsStringSync().trim();
  file.deleteSync();
  return cmd;
}