const express = require('express');
const http = require('http');
const { Server } = require('socket.io');

const app = express();
const server = http.createServer(app);
const io = new Server(server);

app.use(express.static('public'));

let rootFiles = [];

io.on('connection', (socket) => {
    socket.emit('sync_files', rootFiles);

    socket.on('upload_file', (fileData) => {
        rootFiles.push(fileData);
        io.emit('sync_files', rootFiles);
    });

    socket.on('delete_file', (index) => {
        if (rootFiles[index]) {
            rootFiles.splice(index, 1);
            io.emit('sync_files', rootFiles);
        }
    });
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
    console.log(`Server attivo sulla porta ${PORT}`);
});
